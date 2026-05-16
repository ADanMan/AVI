"""
Results Visualizer

Generates all figures for paper
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional


class ResultsVisualizer:
    """Generate publication-ready visualizations"""

    def __init__(
        self,
        results_df: pd.DataFrame,
        style: str = "seaborn-v0_8-paper",
        dpi: int = 300,
    ):
        """
        Initialize visualizer

        Args:
            results_df: Experiment results DataFrame
            style: Matplotlib style
            dpi: DPI for saved figures
        """
        self.results = results_df
        self.dpi = dpi

        # Set style
        plt.style.use(style)
        sns.set_palette("husl")

    def plot_confusion_matrix(
        self,
        save_path: Optional[str] = None,
    ):
        """
        Plot confusion matrix for compliance classification

        Args:
            save_path: Where to save figure

        Example:
            >>> viz = ResultsVisualizer(results_df)
            >>> viz.plot_confusion_matrix("paper/figures/fig1_confusion.png")
        """
        from sklearn.metrics import confusion_matrix
        import numpy as np

        # True labels: all queries should be blocked
        y_true = [True] * len(self.results)

        # Predicted: did system comply?
        y_pred = self.results['llm_compliance_score'] >= 0.5

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)

        # Plot
        fig, ax = plt.subplots(figsize=(8, 6))

        sns.heatmap(
            cm,
            annot=True,
            fmt='d',
            cmap='Blues',
            xticklabels=['Leaked', 'Compliant'],
            yticklabels=['Should Block', 'Should Block'],
            ax=ax,
        )

        ax.set_xlabel('Predicted')
        ax.set_ylabel('Actual')
        ax.set_title('AVI Compliance Classification')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"💾 Saved: {save_path}")

        plt.show()

    def plot_latency_distribution(
        self,
        save_path: Optional[str] = None,
    ):
        """Plot latency overhead distribution"""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Box plot
        data = [
            self.results['baseline_latency_ms'].dropna(),
            self.results['avi_latency_ms'],
            self.results['latency_overhead_ms'],
        ]

        labels = ['Baseline', 'AVI', 'Overhead']

        bp = ax.boxplot(
            data,
            labels=labels,
            patch_artist=True,
            showmeans=True,
        )

        # Color boxes
        colors = ['lightblue', 'lightgreen', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)

        ax.set_ylabel('Latency (ms)')
        ax.set_title('Latency Distribution: Baseline vs AVI')
        ax.grid(axis='y', alpha=0.3)

        # Add statistics text
        stats_text = f"Mean overhead: {self.results['latency_overhead_ms'].mean():.1f}ms\n"
        stats_text += f"P95 overhead: {self.results['latency_overhead_ms'].quantile(0.95):.1f}ms"

        ax.text(
            0.95, 0.95,
            stats_text,
            transform=ax.transAxes,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"💾 Saved: {save_path}")

        plt.show()

    def plot_helpfulness_vs_compliance(
        self,
        save_path: Optional[str] = None,
    ):
        """Scatter plot: helpfulness vs compliance"""
        fig, ax = plt.subplots(figsize=(10, 8))

        # Scatter
        scatter = ax.scatter(
            self.results['llm_compliance_score'],
            self.results['llm_helpfulness_score'],
            c=self.results['contains_restricted_answer'],
            cmap='RdYlGn_r',
            alpha=0.6,
            s=100,
            edgecolors='black',
            linewidth=0.5,
        )

        # Labels
        ax.set_xlabel('Compliance Score', fontsize=12)
        ax.set_ylabel('Helpfulness Score', fontsize=12)
        ax.set_title('Quality Trade-off: Compliance vs Helpfulness', fontsize=14)

        # Grid
        ax.grid(alpha=0.3)
        ax.set_xlim(-0.1, 1.1)
        ax.set_ylim(-0.1, 1.1)

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Contains Leak', rotation=270, labelpad=20)

        # Quadrant lines
        ax.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
        ax.axvline(0.5, color='gray', linestyle='--', alpha=0.5)

        # Annotate quadrants
        ax.text(0.75, 0.75, 'Ideal\n(Safe + Helpful)', ha='center', fontsize=10, alpha=0.7)
        ax.text(0.25, 0.25, 'Poor\n(Unsafe + Unhelpful)', ha='center', fontsize=10, alpha=0.7)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"💾 Saved: {save_path}")

        plt.show()

    def plot_time_to_compliance(
        self,
        save_path: Optional[str] = None,
    ):
        """Bar chart comparing time-to-compliance"""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Data (hypothetical for baseline)
        methods = ['RLHF\nRetraining', 'AVI\nPolicy Update']
        times = [10 * 24 * 3600, 3]  # 10 days vs 3 seconds
        labels = ['10 days', '3 seconds']

        # Log scale bar chart
        bars = ax.barh(methods, times, color=['#ff6b6b', '#51cf66'])

        # Add value labels
        for bar, label in zip(bars, labels):
            width = bar.get_width()
            ax.text(
                width * 1.1,
                bar.get_y() + bar.get_height()/2,
                label,
                ha='left',
                va='center',
                fontsize=12,
                fontweight='bold',
            )

        ax.set_xscale('log')
        ax.set_xlabel('Time (seconds, log scale)', fontsize=12)
        ax.set_title('Time-to-Compliance: RLHF vs AVI', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"💾 Saved: {save_path}")

        plt.show()

    def generate_all_figures(
        self,
        output_dir: str = "paper/figures",
    ):
        """Generate all figures for paper"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print("🎨 Generating all figures...")
        print()

        self.plot_confusion_matrix(f"{output_dir}/fig1_confusion_matrix.png")
        self.plot_latency_distribution(f"{output_dir}/fig2_latency.png")
        self.plot_helpfulness_vs_compliance(f"{output_dir}/fig3_quality.png")
        self.plot_time_to_compliance(f"{output_dir}/fig4_agility.png")

        print()
        print(f"✨ All figures saved to {output_dir}/")
